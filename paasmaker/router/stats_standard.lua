
-- NOTES:
-- Lua Redis scripts can't seem to return a table with named keys,
-- so we have to do some mangling to return a table with just indexes.
-- You'll need to match up the figures on the other side based on this
-- script, but the unit tests will make sure this is written correctly.

-- Assign the inputs to nicer names.
local list_type = ARGV[1]
local input_name = ARGV[2]
local input_id = ARGV[3]

-- Constants that describe what we're doing.
local METRICS = {
	'bytes',
	'1xx',
	'1xx_percentage',
	'2xx',
	'2xx_percentage',
	'3xx',
	'3xx_percentage',
	'4xx',
	'4xx_percentage',
	'5xx',
	'5xx_percentage',
	'requests',
	'time',
	'timecount',
	'time_average',
	'nginxtime',
	'nginxtime_average'
}

local AVERAGES = {{'time', 'timecount'}, {'nginxtime', 'requests'}}
local PERCENTAGES = {{'1xx', 'requests'}, {'2xx', 'requests'}, {'3xx', 'requests'}, {'4xx', 'requests'}, {'5xx', 'requests'}}

-- Convert METRICS into a table so we can look up the index of a named
-- metric
local METRICS_INDEXES = {}
for metricindex, metric in ipairs(METRICS) do
	METRICS_INDEXES[metric] = metricindex
end

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

-- Prepare the initial output.
local output = {}
for metricindex, metric in ipairs(METRICS) do
	output[metricindex] = 0
end

-- For each vtid...
for vtidindex, vtid in ipairs(vtids) do
	local stats = redis.call('hgetall', list_type .. ':' .. vtid)
	-- hgetall returns an array, where:
	-- 1: keyname
	-- 2: value
	-- 3: keyname-2
	-- 4: value-2
	-- So we peek through it one pair of keys at a time.
	for seekindex = 1, #stats, 2 do
		local metric_name = stats[seekindex]
		local metric_value = stats[seekindex + 1]

		if METRICS_INDEXES[metric_name] ~= nil then
			local metricindex = METRICS_INDEXES[metric_name]
			output[metricindex] = output[metricindex] + metric_value
		end
	end
end

-- Now post-process the results.

-- Calculate averages first.
for avgindex, averagemeta in ipairs(AVERAGES) do
	local dividend = output[METRICS_INDEXES[averagemeta[1]]]
	local divisor = output[METRICS_INDEXES[averagemeta[2]]]

	if divisor > 0 then
		local output_key = averagemeta[1] .. '_average'
		output[METRICS_INDEXES[output_key]] = dividend / divisor
	end
end

-- And now the percentages. Redis considers the result numbers integers and
-- ditches any fractional component, so we return 5 digits (effectively allowing
-- two decimal places). You'll need to divide the result by 100 on the receiving end.
for percentindex, percentmeta in ipairs(PERCENTAGES) do
	local dividend = output[METRICS_INDEXES[percentmeta[1]]]
	local divisor = output[METRICS_INDEXES[percentmeta[2]]]

	if divisor > 0 then
		local output_key = percentmeta[1] .. '_percentage'
		output[METRICS_INDEXES[output_key]] = (dividend / divisor) * 10000
	end
end

return output