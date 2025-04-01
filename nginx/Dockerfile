# Stage 1: Extract libz.so.1 and libz.so.1.2.13 from debian:bookworm-slim
FROM debian:bookworm-slim AS zlib-extract

RUN apt-get update && \
    apt-get install --no-install-recommends -y zlib1g && \
    cp /usr/lib/x86_64-linux-gnu/libz.so.1* /tmp/

# Stage 2: Upgrade setuptools in isolation
FROM python:3.11-slim AS python-tools

# Upgrade setuptools to 70.0.0 to fix CVE-2023-6345
RUN pip install setuptools==70.0.0

# Stage 3: Build the application
FROM nginx:stable-perl

# Remove unnecessary system packages
RUN apt-get update && \
    # Remove libexpat1 to fix CVE-2024-8176, & CVE-2023-52425
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libexpat1 && \
    # Remove libbluetooth3 to fix CVE-2023-44431 & CVE-2023-51596
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libbluetooth3 && \
    # Remove perl to fix CVE-2023-31484
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge --allow-remove-essential -y perl-base && \
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y perl-modules-5.36 && \
    # Remove libxslt1.1 to fix CVE-2024-55549 & CVE-2025-24855
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libxslt1.1 && \
    # Remove libxml2 to fix CVE-2024-25062, CVE-2024-56171, CVE-2025-24928, & CVE-2025-27113
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libxml2 && \
    # Remove libldap-2.5-0 to fix CVE-2023-2953
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libldap-2.5-0 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy upgraded setuptools from stage 2 to fix CVE-2024-6345
COPY --from=python-tools /usr/local/lib/python3.11/site-packages/setuptools* /usr/lib/python3/dist-packages/

# Remove libz1g to fix CVE-2023-45853
# WARNING: This will uninstall the package manager, which will prevent us from removing other packages, so this should be done last
RUN dpkg --purge --force-all zlib1g || true

# Copy extracted libz shared objects from stage 1 to fix CVE-2023-45853
COPY --from=zlib-extract /tmp/libz.so.1 /usr/lib/x86_64-linux-gnu/libz.so.1
COPY --from=zlib-extract /tmp/libz.so.1.2.13 /usr/lib/x86_64-linux-gnu/libz.so.1.2.13
