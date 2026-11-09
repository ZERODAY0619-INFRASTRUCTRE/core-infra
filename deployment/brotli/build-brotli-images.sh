#!/bin/sh
set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
package_directory=$(mktemp -d)
trap 'rm -rf "$package_directory"' EXIT HUP INT TERM

package_base=https://dl-cdn.alpinelinux.org/alpine/v3.24/main/aarch64
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
    "$package_base/brotli-libs-1.2.1-r0.apk" \
    --output "$package_directory/brotli-libs-1.2.1-r0.apk"
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
    "$package_base/brotli-1.2.1-r0.apk" \
    --output "$package_directory/brotli-1.2.1-r0.apk"

printf '%s  %s\n' \
    f802b9d5a329c216f02e73607cb8f662c434767e41686367ac0afcf6d0d45d64 "$package_directory/brotli-libs-1.2.1-r0.apk" \
    9ed511ac8d0820524dfb69ebbb3280535202cbd548d5ff2bbce6e581ac24c6f9 "$package_directory/brotli-1.2.1-r0.apk" \
    | sha256sum --check --status

sudo -n docker build --network none \
    --file "$script_directory/geoipupdate.Dockerfile" \
    --tag cpm-geoipupdate:8.0.0-brotli-1.2.1-r0 "$package_directory"
sudo -n docker build --network none \
    --file "$script_directory/mautrix-discord.Dockerfile" \
    --tag mautrix-discord:sha065405ca-brotli-1.2.1-r0 "$package_directory"

sudo -n docker build --network host \
    --build-arg BASE_IMAGE=cpm-geoipupdate:8.0.0-brotli-1.2.1-r0 \
    --file "$script_directory/alpine-secure.Dockerfile" \
    --tag cpm-geoipupdate:8.0.0-security-20261024 "$script_directory"
sudo -n docker build --network host \
    --build-arg BASE_IMAGE=mautrix-discord:sha065405ca-brotli-1.2.1-r0 \
    --file "$script_directory/alpine-secure.Dockerfile" \
    --tag mautrix-discord:security-20261024 "$script_directory"

sudo -n docker build --network host \
    --file "$script_directory/geoipupdate-go-secure.Dockerfile" \
    --tag cpm-geoipupdate:8.0.0-security-go-20261024 "$script_directory"

sudo -n docker build --network host \
    --file "$script_directory/mautrix-discord-go-secure.Dockerfile" \
    --tag mautrix-discord:security-go-20261024 "$script_directory"
