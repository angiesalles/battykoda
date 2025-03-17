# Deploying BattyCoda with Cloudflare

This guide explains how to deploy BattyCoda with Cloudflare for domain management and authentication.

## Domain Setup

1. **Register your domain** (battycoda.com) if you haven't already
2. **Add the domain to Cloudflare**:
   - Create a Cloudflare account at https://dash.cloudflare.com/sign-up
   - Add your site by clicking "Add a Site" and entering your domain name
   - Cloudflare will scan your DNS records
   - Update your domain's nameservers with your registrar to point to Cloudflare's nameservers
   - Follow the instructions provided by Cloudflare to complete the process

## DNS Configuration

1. **Configure DNS records** for your BattyCoda server:
   - Go to the DNS tab in your Cloudflare dashboard
   - Add an A record:
     - Type: A
     - Name: @
     - IPv4 address: [Your server's public IP address]
     - TTL: Auto
     - Proxy status: Proxied (orange cloud)

2. **Add www subdomain** (optional):
   - Type: CNAME
   - Name: www
   - Target: @
   - TTL: Auto
   - Proxy status: Proxied (orange cloud)

## Cloudflare Access Configuration

Cloudflare Access provides an authentication layer in front of your application:

1. **Enable Zero Trust**:
   - Go to Cloudflare dashboard
   - Click on "Zero Trust" in the sidebar
   - Complete the setup process

2. **Create an Access application**:
   - In Zero Trust dashboard, go to "Access" > "Applications"
   - Click "Add an application"
   - Select "Self-hosted" application
   - Configure the application:
     - Name: BattyCoda
     - Session duration: 24 hours (or your preferred duration)
     - Application domain: battycoda.com
     - Add path (optional): / (to protect entire site)

3. **Configure authentication policies**:
   - Go to the Policies tab for your application
   - Click "Add a policy"
   - Name your policy (e.g., "BattyCoda Access")
   - Configure who can access:
     - Choose authentication methods (email domains, specific emails, etc.)
   - Click "Save"

## Application Configuration

Configure BattyCoda to work with Cloudflare Access:

1. **Update your environment variables**:

```bash
# Add these to your environment or .env file
CLOUDFLARE_ACCESS_ENABLED=True
CLOUDFLARE_AUDIENCE=your-audience-tag
```

The `CLOUDFLARE_AUDIENCE` value can be found in your Cloudflare Access application settings.

2. **Install required dependencies**:

```bash
pip install pyjwt cryptography
```

3. **Test the integration**:

   - Start your BattyCoda application
   - Access it through your Cloudflare domain (e.g., https://battycoda.com)
   - You should be prompted to authenticate through Cloudflare's login screen
   - After authentication, you'll be redirected to BattyCoda's interface

## Security Considerations

1. **SSL/TLS**:
   - Cloudflare will handle SSL/TLS encryption by default
   - Set SSL/TLS encryption mode to "Full" or "Full (strict)" in the Cloudflare dashboard

2. **Firewall Rules**:
   - Restrict direct access to your server by configuring your server firewall to only accept connections from Cloudflare's IP ranges
   - Cloudflare publishes their IP ranges at: https://www.cloudflare.com/ips/

3. **Origin Server**:
   - Ensure your origin server is properly secured
   - Consider implementing additional WAF rules in Cloudflare

## Troubleshooting

If you experience issues with the Cloudflare Access integration:

1. **Check BattyCoda logs** for any authentication errors:
   ```bash
   ./view_logs.sh
   ```

2. **Verify Cloudflare configuration**:
   - Make sure the application domain exactly matches your site
   - Check that your authentication policy is correctly configured

3. **Test JWT token validation**:
   - You can manually validate a token using the JWT debugger at https://jwt.io

4. **Contact Cloudflare support** if you continue to have issues