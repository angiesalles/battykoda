#!/bin/bash
set -e

# Ensure script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root. Try using sudo."
    exit 1
fi

# Load domain from .env.local if available
if [ -f "/home/ubuntu/battycoda/.env.local" ]; then
    source /home/ubuntu/battycoda/.env.local
    DOMAIN_NAME=${DOMAIN_NAME:-"boergens.net"}
    echo "Using domain: $DOMAIN_NAME"
else
    DOMAIN_NAME="boergens.net"
    echo "Using default domain: $DOMAIN_NAME"
fi

# Back up current iptables rules
echo "Backing up current iptables rules..."
iptables-save > /home/ubuntu/battycoda/iptables-backup-$(date +%Y%m%d%H%M%S).rules

# Permanently remove the port forwarding rules
echo "Permanently removing port 80 forwarding rules..."
iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8060 || echo "Rule #1 not found or already removed"
iptables -t nat -D OUTPUT -o lo -p tcp --dport 80 -j REDIRECT --to-port 8060 || echo "Rule #2 not found or already removed"
iptables -t nat -D OUTPUT -p tcp --dport 80 -j REDIRECT --to-port 8060 || echo "Rule #3 not found or already removed"

# Verify the rule is removed
echo "Verifying port forwarding rules are removed..."
iptables -t nat -L -n | grep "redir ports 8060" && echo "Warning: Some port forwarding rules still exist" || echo "Port forwarding rules successfully removed"

# Make the changes permanent
if command -v netfilter-persistent &> /dev/null; then
    echo "Saving iptables rules permanently..."
    netfilter-persistent save
elif [ -f /etc/debian_version ]; then
    echo "Installing iptables-persistent to make rules permanent..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
    netfilter-persistent save
else
    echo "Note: Consider installing iptables-persistent to make these changes survive reboots"
    echo "For Ubuntu/Debian: apt-get install -y iptables-persistent"
    echo "For CentOS/RHEL: yum install -y iptables-services && systemctl enable iptables"
fi

# Make sure Nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    apt-get update
    apt-get install -y nginx
fi

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update
    apt-get install -y certbot python3-certbot-nginx
fi

# Stop services for certificate issuance
echo "Stopping Nginx to free port 80 for certificate issuance..."
systemctl stop nginx || true

# Get the certificate using standalone mode for both main domain and www subdomain
echo "Obtaining SSL certificate for $DOMAIN_NAME and www.$DOMAIN_NAME..."
certbot certonly --standalone -d $DOMAIN_NAME -d www.$DOMAIN_NAME --agree-tos --email admin@$DOMAIN_NAME

# Set up Nginx with proper HTTPS configuration
echo "Setting up Nginx for HTTPS..."
cat > /etc/nginx/sites-available/$DOMAIN_NAME <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;
    
    # Redirect all HTTP traffic to HTTPS
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN_NAME www.$DOMAIN_NAME;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/$DOMAIN_NAME/chain.pem;

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

# Enable the site
ln -sf /etc/nginx/sites-available/$DOMAIN_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Test Nginx configuration
nginx -t

# Update Django settings
echo "Updating Django settings for HTTPS..."
sed -i 's/SECURE_SSL_REDIRECT = False/SECURE_SSL_REDIRECT = True/' /home/ubuntu/battycoda/config/settings.py
sed -i 's/SESSION_COOKIE_SECURE = False/SESSION_COOKIE_SECURE = True/' /home/ubuntu/battycoda/config/settings.py
sed -i 's/CSRF_COOKIE_SECURE = False/CSRF_COOKIE_SECURE = True/' /home/ubuntu/battycoda/config/settings.py
sed -i 's/# SECURE_HSTS_SECONDS/SECURE_HSTS_SECONDS/' /home/ubuntu/battycoda/config/settings.py
sed -i 's/# SECURE_HSTS_INCLUDE_SUBDOMAINS/SECURE_HSTS_INCLUDE_SUBDOMAINS/' /home/ubuntu/battycoda/config/settings.py
sed -i 's/# SECURE_HSTS_PRELOAD/SECURE_HSTS_PRELOAD/' /home/ubuntu/battycoda/config/settings.py

# Start Nginx
echo "Starting Nginx..."
systemctl start nginx
systemctl enable nginx

# Set up automatic renewal
echo "Setting up automatic renewal of SSL certificates..."
cat > /etc/cron.monthly/certbot-renewal <<EOF
#!/bin/bash

# Renew certificates
certbot renew --pre-hook "systemctl stop nginx" --post-hook "systemctl start nginx"
EOF

chmod +x /etc/cron.monthly/certbot-renewal

echo "==================================================================="
echo "HTTPS setup complete for $DOMAIN_NAME!"
echo "==================================================================="
echo " "
echo "The port 80 forwarding rules have been permanently removed."
echo "Nginx is now properly configured to:"
echo "  - Listen on ports 80 and 443"
echo "  - Redirect HTTP to HTTPS"
echo "  - Forward HTTPS traffic to your Django application on port 8060"
echo " "
echo "If your application relied on the port forwarding, you may need to"
echo "update your Docker setup to have the web service listen only on"
echo "localhost:8060 instead of binding to all interfaces."
echo " "
echo "To check if everything is working:"
echo "  1. Visit https://$DOMAIN_NAME in your browser"
echo "  2. Verify that HTTP redirects to HTTPS"
echo "  3. Check that your application works correctly over HTTPS"
echo " "
echo "SSL certificates will be automatically renewed monthly."