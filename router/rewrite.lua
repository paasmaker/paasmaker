local redis = require("resty.redis")
local red = redis:new()

local ok, err = red:connect(ngx.var.redis_host, ngx.var.redis_port)
if err then
	ngx.say(ngx.HTTP_FORBIDDEN)
	return
end

local ok, err = red:get(ngx.req.get_headers()["Host"])
ngx.log(ngx.DEBUG, ok)
ngx.log(ngx.DEBUG, err)
if not ok then
	ngx.log(ngx.DEBUG, "Failed, exiting...")
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end
ngx.log(ngx.DEBUG, "Continuing...")
ngx.var.upstream = ok
ngx.log(ngx.DEBUG, ngx.var.upstream)    
