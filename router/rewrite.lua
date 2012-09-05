-- Include the relevant libraries.
local redis = require("resty.redis")
local red = redis:new()

-- Connect to nginx. Or fail with a 500 server error if we can't.
local ok, err = red:connect(ngx.var.redis_host, ngx.var.redis_port)
ngx.log(ngx.DEBUG, ok)
ngx.log(ngx.DEBUG, err)
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

local ok, err = red:get(host)
ngx.log(ngx.DEBUG, ok)
ngx.log(ngx.DEBUG, err)
if err then
	-- Failed to fetch from Redis? 500 error.
	ngx.log(ngx.DEBUG, "Failed, exiting...")
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end
if ok == ngx.null then
	-- Can't find a match? Not found.
	ngx.log(ngx.DEBUG, "Not found...")
	ngx.exit(ngx.HTTP_NOT_FOUND)
end

-- Return the value back to the calling script.
ngx.log(ngx.DEBUG, "Continuing...")
ngx.var.upstream = ok
ngx.log(ngx.DEBUG, ngx.var.upstream)
