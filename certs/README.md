# SSL / TLS Certificate Directory
Place production or development Let's Encrypt certificates here:
- `live/foodbridge.org/fullchain.pem`
- `live/foodbridge.org/privkey.pem`

For local testing without Certbot:
```bash
mkdir -p live/foodbridge.org
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout live/foodbridge.org/privkey.pem \
  -out live/foodbridge.org/fullchain.pem \
  -subj "/CN=foodbridge.org"
```

