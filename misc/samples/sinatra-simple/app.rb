require 'sinatra'

get '/' do
	"Hello, world!"
end

get '/environ' do
	response = "<pre>"
	ENV.each_pair do |k,v|
		response += k + " => " + v + "\n"
	end
	response += "</pre>"

	return response
end