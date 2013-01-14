#!/bin/bash

USERNAME="$1"
EMAIL="$2"
NAME="$3"
PASSWORD="$4"
SUPERKEY="$5"

if [ "$5" == "" ];
then
	echo "Usage: $0 username email fullname password superkey"
	exit 1
fi

./pm-command.py user-create $USERNAME $EMAIL "$NAME" $PASSWORD --superkey=$SUPERKEY
./pm-command.py role-create Administrator ALL --superkey=$SUPERKEY
./pm-command.py workspace-create Test test {} --superkey=$SUPERKEY
./pm-command.py role-allocate 1 1 --superkey=$SUPERKEY

