FROM eclipse-mosquitto:2.0.22

COPY mosquitto.conf /mosquitto/config/mosquitto.conf
COPY entrypoint.sh /usr/local/bin/mosquitto-entrypoint

ENTRYPOINT ["/usr/local/bin/mosquitto-entrypoint"]
CMD ["mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]
