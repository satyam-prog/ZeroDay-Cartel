# ============================================================================
# FoodBridge - Production Gateway & Static Web Container
# Base Image: Alpine Linux with Nginx unprivileged
# ============================================================================

FROM nginx:1.27-alpine

# Remove default configuration
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*

# Copy hardened nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy production web assets
COPY index.html /usr/share/nginx/html/index.html
COPY privacy.html /usr/share/nginx/html/privacy.html
COPY terms.html /usr/share/nginx/html/terms.html
COPY favicon.svg /usr/share/nginx/html/favicon.svg
COPY CNAME /usr/share/nginx/html/CNAME
COPY assets /usr/share/nginx/html/assets

# Create non-root directories and set permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]

