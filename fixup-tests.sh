#!/bin/bash

# extract Blosxom version from the CGI - we could do with a param for this
VERSION=$( perl -n -e 'print $1 if m/^\$version = "([^"]+)"/;' blosxom.cgi )
SED_VERSION="/generator/{ s/(blosxom.)2\.[0-9][0-9.+a-z]*\>/\1$VERSION/ }"
SED_WHITESP="s/^ +//" 

for F in "$@"; do
	echo "Get size: $F"
	grep -q '^Content-Type:' "$F" && CT=1 || CT=0
	# SIZE=$( cat "$F" | sed -E -e '1,/^\r$/d' -e "$SED_WHITESP" | wc -c ) || continue
	SIZE=$( cat "$F" | sed -E -e '1,/^\r$/d' -e "$SED_VERSION" | wc -c ) || continue
	echo "SIZE:$SIZE, CT:$CT"
	TEMP="$F.$$"
	{
		[ "$CT" = 1 ] && echo -n -e "Content-length: $SIZE\r\n"
		grep -v "^Content-length:" "$F" | sed -E -e "$SED_VERSION" # -e "SED_WHITESP"
	} > "$TEMP" && mv "$TEMP" "$F"
done
