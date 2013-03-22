var http = require('http');
var url = require('url');
var fs = require('fs');

var port_number = process.env.PM_PORT || 8000;

http.createServer(function (req, res) {
  var request = url.parse(req.url, true);
  var action = request.pathname;

  if (action == '/') {
    res.writeHead(200, {'Content-Type': 'text/html'});
    var img = fs.readFile('./index.html', function(e, data) {
	  res.end(data, 'utf8');
	});
  }

}).listen(port_number, function() {
  console.log("Demo web server listening at http://locahost:" + port_number);
});
