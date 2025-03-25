#!/bin/bash
# Script to generate and install Nginx configuration for BattyCoda
# with support for SSL/HTTPS and file upload size limits

# Ensure .env file exists
if [ ! -f .env ]; then
  echo "Error: .env file not found!"
  echo "Please create a .env file with DOMAIN_NAME and MAX_UPLOAD_SIZE_MB variables."
  exit 1
fi

# Load environment variables from .env
source .env

# Verify required variables
if [ -z "$DOMAIN_NAME" ]; then
  echo "Error: DOMAIN_NAME not set in .env file!"
  exit 1
fi

# Use default for upload size if not specified
MAX_UPLOAD_SIZE_MB=${MAX_UPLOAD_SIZE_MB:-100}

echo "Generating Nginx configuration with:"
echo " - Domain: $DOMAIN_NAME"
echo " - Max upload size: ${MAX_UPLOAD_SIZE_MB}M"

# Check if SSL certificates exist for this domain
CERT_PATH="/etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem"
KEY_PATH="/etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem"
CHAIN_PATH="/etc/letsencrypt/live/$DOMAIN_NAME/chain.pem"

# Generate the Nginx configuration
cat > /etc/nginx/sites-available/battycoda.conf << EOF
# HTTP server - either serves content or redirects to HTTPS
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    client_max_body_size ${MAX_UPLOAD_SIZE_MB}M;

EOF

# If SSL certificates exist, set up redirection to HTTPS
if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
  echo "SSL certificates found. Setting up HTTPS redirection..."
  cat >> /etc/nginx/sites-available/battycoda.conf << EOF
    # Redirect all HTTP traffic to HTTPS
    return 301 https://\$host\$request_uri;
}

# HTTPS server - serves content
server {
    listen 443 ssl;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    client_max_body_size ${MAX_UPLOAD_SIZE_MB}M;

    ssl_certificate $CERT_PATH;
    ssl_certificate_key $KEY_PATH;
    ssl_trusted_certificate $CHAIN_PATH;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";
EOF
else
  echo "No SSL certificates found. Setting up HTTP only..."
  # Just continue with HTTP configuration
fi

# Add common location blocks
cat >> /etc/nginx/sites-available/battycoda.conf << EOF
    location /static/ {
        alias /home/ubuntu/battycoda/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/battycoda/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8060;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Create symbolic link if it doesn't exist
if [ ! -L /etc/nginx/sites-enabled/battycoda.conf ]; then
  ln -sf /etc/nginx/sites-available/battycoda.conf /etc/nginx/sites-enabled/
fi

# Test and reload nginx
nginx -t 
if [ $? -eq 0 ]; then
  systemctl reload nginx
  echo "Nginx configuration updated and reloaded successfully."
  
  # Provide instructions for SSL setup if needed
  if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
    echo ""
    echo "NOTE: No SSL certificates were found. To enable HTTPS, run:"
    echo "sudo certbot --nginx -d $DOMAIN_NAME -d www.$DOMAIN_NAME"
    echo "Then run this script again to apply all settings."
  fi
else
  echo "Error in Nginx configuration. Please check the syntax."
  exit 1
fi