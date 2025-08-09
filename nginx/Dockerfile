FROM nginx:alpine

# No need to install gettext anymore unless you still want it for something else
# RUN apk add --no-cache gettext

# Remove default config to avoid conflicts
RUN rm /etc/nginx/conf.d/default.conf

# Start nginx normally in the foreground
CMD ["nginx", "-g", "daemon off;"]
