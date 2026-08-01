#!/bin/sh
set -e
mkdir -p public
cp dashboard/index.html dashboard/app.js dashboard/i18n-ur.js dashboard/push.js dashboard/sw.js dashboard/themes.css dashboard/robots.txt dashboard/site.webmanifest dashboard/favicon.svg dashboard/favicon-96.png dashboard/apple-touch-icon.png dashboard/icon-192.png dashboard/icon-512.png dashboard/logo.svg dashboard/logo-mark.svg dashboard/logo-terminal.svg dashboard/og.jpg dashboard/og.png public/
cp -r state public/state
printf '' > public/.nojekyll
