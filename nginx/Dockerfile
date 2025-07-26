FROM nginx:alpine
# Install envsubst for template processing
RUN apk add --no-cache gettext
# Remove default config
RUN rm /etc/nginx/conf.d/default.conf
# Command to process template on startup
CMD ["sh", "-c", "envsubst '${ACTIVE_APP}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]