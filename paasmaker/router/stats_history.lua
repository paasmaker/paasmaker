
-- Assign the inputs to nicer names.
local list_type = ARGV[1]
local input_name = ARGV[2]
local input_id = ARGV[3]
-- The list of metrics is JSON encoded, to get it
-- across the Python/Redis boundary.
local metrics = cjson.decode(ARGV[4])
local start_time = tonumber(ARGV[5])
local end_time = tonumber(ARGV[6])

-- Figure out the version type list from the input.
local vtids = {}
if input_name == 'version_type' then
	vtids = {input_id}
elseif input_name == 'uncaught' then
	vtids = {'null'}
elseif input_name == 'pacemaker' then
	vtids = {'pacemaker'}
else
	-- The key that holds the vtset.
	local vtset_key = input_name .. ":" .. input_id

	-- Fetch all the vtids for this set.
	vtids = redis.call('smembers', vtset_key)
end

-- -- Prepare the initial output.
local output = {}
for metricindex, metric in ipairs(metrics) do
	output[metric] = {}

	-- Uncomment this to test out the summing part of the main loop.
	-- TODO: Make a test to test this automatically.
	-- output[metric]['' .. end_time] = 13
end

-- Calculate the box boundaries.
-- There is one key per hour, so convert start_time and
-- end_time into boundary boxes.
local boundaries = {}
local real_start = start_time - (start_time % 3600)
for boundary = real_start, end_time, 3600 do
	table.insert(boundaries, boundary)
end

-- For each metric...
for metricindex, metric in ipairs(metrics) do
	-- For each vtid...
	for vtidindex, vtid in ipairs(vtids) do
		-- For each boundary...
		for boundaryindex, boundary in ipairs(boundaries) do
			local history_key = list_type .. ':' .. vtid .. ':' .. boundary .. ':' .. metric
			local history = redis.call('hgetall', history_key)
			-- hgetall returns an array, where:
			-- 1: keyname
			-- 2: value
			-- 3: keyname-2
			-- 4: value-2
			-- So we peek through it one pair of keys at a time.
			-- Key is a unix timestamp, and value is the value,
			-- which we sum.
			for seekindex = 1, #history, 2 do
				local timestamp = tonumber(history[seekindex])
				if timestamp >= start_time and timestamp <= end_time then
					local history_value = tonumber(history[seekindex + 1])

					if output[metric][history[seekindex]] ~= nil then
						-- Add this value to the existing one.
						output[metric][history[seekindex]] = output[metric][history[seekindex]] + history_value
					else
						-- New entry.
						output[metric][history[seekindex]] = history_value
					end
				end
			end
		end
	end
end

-- Encode the result to JSON, so we can preserve the keys.
return cjson.encode(output)