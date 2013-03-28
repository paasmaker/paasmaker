--
-- Paasmaker - Platform as a Service
--
-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at http://mozilla.org/MPL/2.0/.
--

-- Paasmaker NGINX LUA router script.

-- Include the relevant libraries.
local redis = require("resty.redis")
local red = redis:new()

-- Connect to Redis. Or fail with a 500 server error if we can't.
local ok, err = red:connect(ngx.var.redis_host, ngx.var.redis_port)
if err then
	ngx.log(ngx.DEBUG, "Unable to connect to redis.")
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

-- Helper function to split strings. From http://lua-users.org/wiki/SplitJoin,
-- using the "Function: true Python semantics for split" section.
function string:split(sSeparator, nMax, bRegexp)
	assert(sSeparator ~= '')
	assert(nMax == nil or nMax >= 1)

	local aRecord = {}

	if self:len() > 0 then
		local bPlain = not bRegexp
		nMax = nMax or -1

		local nField=1 nStart=1
		local nFirst,nLast = self:find(sSeparator, nStart, bPlain)
		while nFirst and nMax ~= 0 do
			aRecord[nField] = self:sub(nStart, nFirst-1)
			nField = nField+1
			nStart = nLast+1
			nFirst,nLast = self:find(sSeparator, nStart, bPlain)
			nMax = nMax-1
		end
		aRecord[nField] = self:sub(nStart)
	end

	return aRecord
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

-- Strip off any port in the host. This is probably
-- against the HTTP spec, but allows for easier testing,
-- and possibly some other magic scenarios.
bits = string.split(host, ':')
host = bits[1] -- Yes, remember that Lua's array indexes start at 1.

-- Convert 'www.foo.com' into '*.foo.com' for a secondary search.
wildcard_host = host:gsub("(.-)[.]", "*.", 1)

-- Set up all our redis keys now.
local redis_host_key = "instances:" .. host
local redis_wildcard_key = "instances:" .. wildcard_host

ngx.log(ngx.DEBUG, "Host: " .. host)
ngx.log(ngx.DEBUG, "Wildcard host: " .. wildcard_host)
ngx.log(ngx.DEBUG, "Redis instances key: " .. redis_host_key)
ngx.log(ngx.DEBUG, "Redis wildcard instances key: " .. redis_wildcard_key)

-- Start the pipeline, and ask all the questions.
-- Why a pipeline? To reduce the round trips to the redis instance.
red:init_pipeline()
red:srandmember(redis_host_key)
red:srandmember(redis_wildcard_key)

-- Commit the pipeline and fetch the results.
local results, err = red:commit_pipeline()
if not results then
	ngx.log(ngx.DEBUG, "Failed to query redis, exiting...")
	ngx.exit(ngx.HTTP_INTERNAL_SERVER_ERROR)
end

ngx.log(ngx.DEBUG, "Raw results: ")
ngx.log(ngx.DEBUG, results[1])
ngx.log(ngx.DEBUG, results[2])

-- Process the results.
if results[1] ~= ngx.null then
	ngx.log(ngx.DEBUG, "Found and using direct " .. host)
	-- Explode the bits.
	bits = string.split(results[1], '#')
	ngx.var.upstream = bits[1]
	ngx.var.versiontypekey = bits[2]
	ngx.var.nodekey = bits[3]
	ngx.var.instancekey = bits[4]
else
	if results[2] ~= ngx.null then
		ngx.log(ngx.DEBUG, "Found and using wildcard " .. wildcard_host)

		-- Explode the bits.
		bits = string.split(results[2], '#')
		ngx.var.upstream = bits[1]
		ngx.var.versiontypekey = bits[2]
		ngx.var.nodekey = bits[3]
		ngx.var.instancekey = bits[4]
	else
		-- No match.
		ngx.log(ngx.DEBUG, "Not found.")
		ngx.exit(ngx.HTTP_NOT_FOUND)
	end
end

ngx.log(ngx.DEBUG, "Upstream result: " .. ngx.var.upstream)
ngx.log(ngx.DEBUG, "Log key: " .. ngx.var.versiontypekey)