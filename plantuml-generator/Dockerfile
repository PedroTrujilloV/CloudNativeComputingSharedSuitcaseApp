FROM plantuml/plantuml:latest
ENTRYPOINT ["/entrypoint.sh"]
COPY entrypoint.sh /entrypoint.sh
USER root
RUN chmod +x /entrypoint.sh