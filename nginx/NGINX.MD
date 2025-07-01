This creates:

nginx/certs/cert.pem ✅

nginx/certs/key.pem ✅
openssl req -x509 -newkey rsa:2048 -nodes -keyout nginx/certs/key.pem -out nginx/certs/cert.pem -days 730

or 

sudo openssl req -x509 -nodes -days 730 -newkey rsa:2048 \
  -keyout /etc/ssl/private/nginx-selfsigned.key \
  -out /etc/ssl/certs/nginx-selfsigned.crt
