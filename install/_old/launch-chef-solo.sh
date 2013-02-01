#!/bin/bash
set +x

HERE=`pwd`

if [ ! -d ".chef-temp" ]; then
	mkdir ".chef-temp"
fi

echo "file_cache_path \"$HERE/.chef-temp\"" > .solo.rb
echo "cookbook_path \"$HERE\"" >> .solo.rb

chef-solo -c .solo.rb -j node.json