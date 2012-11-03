-- Include the relevant libraries.
local redis = require("resty.redis")
local red = redis:new()

-- Connect to Redis. Or fail with a 500 server error if we can't.
local ok, err = red:connect(ngx.var.redis_host, ngx.var.redis_port)
if err then
	ngx.say(ngx.HTTP_INTERNAL_SERVER_ERROR)
	return
end

-- Now look up the hostname.
local host = ngx.req.get_headers()["Host"]
ngx.log(ngx.DEBUG, host)
if not host then
	-- Check lowercase host.
	host = ngx.req.get_headers()['host']
	ngx.log(ngx.DEBUG, host)
	if not host then
		-- No Host: header? 400, Bad request.
		ngx.log(ngx.DEBUG, "No Host: header")
		ngx.exit(ngx.HTTP_BAD_REQUEST)
	end
end

-- String processing before we proceed.
-- Convert the incoming hostname to lowercase.
host = host:lower()

-- Convert 'www.foo.com' into '*.foo.com' for a secondary search.
wildcard_host = host:gsub("(.-)[.]", "*.", 1)

-- Set up all our redis keys now.
local redis_host_key = "instances_" .. host
local redis_wildcard_key = "instances_" .. wildcard_host
local redis_log_key = "logkey_" .. host
local redis_wildcard_log_key = "logkey_" .. wildcard_host

ngx.log(ngx.DEBUG, "Host: " .. host)
ngx.log(ngx.DEBUG, "Wildcard host: " .. wildcard_host)
ngx.log(ngx.DEBUG, "Redis instances key: " .. redis_host_key)
ngx.log(ngx.DEBUG, "Redis log key: " .. redis_wildcard_key)
ngx.log(ngx.DEBUG, "Redis wildcard key: " .. redis_log_key)
ngx.log(ngx.DEBUG, "Redis wildcard log key: " .. redis_wildcard_log_key)

-- Start the pipeline, and ask all the questions.
-- Why a pipeline? To reduce the round trips to the redis instance.
red:init_pipeline()
red:srandmember(redis_host_key)
red:get(redis_log_key)
red:srandmember(redis_wildcard_key)
red:get(redis_wildcard_log_key)

-- Commit the pipeline and fetch the results.
local results, err = red:commit_pipeline()
if not results then
	ngx.log(ngx.DEBUG, "Failed to query redis, exiting...")
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

-- ngx.log(ngx.DEBUG, "Raw results: ")
-- ngx.log(ngx.DEBUG, results[1])
-- ngx.log(ngx.DEBUG, results[2])
-- ngx.log(ngx.DEBUG, results[3])
-- ngx.log(ngx.DEBUG, results[4])

-- Process the results.
if results[1] ~= ngx.null then
	ngx.log(ngx.DEBUG, "Found and using direct " .. host)
	ngx.var.upstream = results[1]
	ngx.var.logkey = results[2]
else
	if results[3] ~= ngx.null then
		ngx.log(ngx.DEBUG, "Found and using wildcard " .. wildcard_host)
		ngx.var.upstream = results[3]
		ngx.var.logkey = results[4]
	else
		-- No match.
		ngx.log(ngx.DEBUG, "Not found.")
		ngx.exit(ngx.HTTP_NOT_FOUND)
	end
end

ngx.log(ngx.DEBUG, "Upstream result: " .. ngx.var.upstream)
ngx.log(ngx.DEBUG, "Log key: " .. ngx.var.logkey)