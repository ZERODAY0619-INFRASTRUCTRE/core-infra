#!/bin/sh
set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

build_image() {
    base_image=$1
    expected_image_id=$2
    patched_image=$3
    actual_image_id=$(sudo -n docker image inspect --format '{{.Id}}' "$base_image")
    if [ "$actual_image_id" != "$expected_image_id" ]; then
        printf 'Unexpected base image ID for %s: %s\n' "$base_image" "$actual_image_id" >&2
        exit 1
    fi

    sudo -n docker build --network none \
        --build-arg "BASE_IMAGE=$base_image" \
        --file "$script_directory/bun-runtime.Dockerfile" \
        --tag "$patched_image" "$script_directory"
}

build_image cpm-web:a93ba568bc8b-arm64 \
    sha256:3cd33dea9062239463ac703b8db42b6b24611a8c5a1ce5c9fba5cb186ef9eee1 \
    cpm-web:bun-1.4.4-a93ba568bc8b
build_image cpm-web:grafana-proxy-20260922 \
    sha256:6ae978b3878d22edec35d56ab5525e905ea6fffa1d60b334a629dc4958f3b322 \
    cpm-web:bun-1.4.4-grafana-proxy-20260922
build_image cpm-anubis:a93ba568bc8b-arm64 \
    sha256:6f49536950ab1683e494bb50f108bdd15d962fab7a145c71addc3c445a84bf86 \
    cpm-anubis:bun-1.4.4-a93ba568bc8b
