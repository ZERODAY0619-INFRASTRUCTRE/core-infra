FROM alpine:3.23
RUN apk add --no-cache nftables iproute2 python3
COPY entrypoint.sh /entrypoint.sh
COPY certificate-egress.py /certificate-egress.py
ENTRYPOINT ["sh", "/entrypoint.sh"]
