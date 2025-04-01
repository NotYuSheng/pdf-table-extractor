# Stage 1: Extract libz.so.1 and libz.so.1.2.13 from debian:bookworm-slim
FROM debian:bookworm-slim AS zlib-extract

RUN apt-get update && \
    apt-get install --no-install-recommends -y zlib1g && \
    cp /usr/lib/x86_64-linux-gnu/libz.so.1* /tmp/

# Stage 2: Build the application
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files into the container
COPY . .

# Upgrade setuptools to 70.0.0 to fix CVE-2023-6345
RUN pip install setuptools==70.0.0

# Remove unnecessary system packages
RUN apt-get update && \
    # Upgrade libxslt1.1 to 1.1.35-1+deb12u1 to fix CVE-2024-55549, CVE-2025-24855, CVE-2024-55549, CVE-2025-24855, & CVE-2015-9019
    apt-get install --no-install-recommends -y libxslt1.1=1.1.35-1+deb12u1 && \
    # Remove linux-libc-dev to fix CVE-2013-7445, CVE-2019-19449, a bunch of other High CVEs
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y linux-libc-dev && \
    # CVE-2013-7445, CVE-2019-19449, a bunch of other High CVEs
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libexpat1 && \
    # Remove libxml2 to fix CVE-2024-25062, CVE-2024-56171, CVE-2025-24928, & CVE-2025-27113
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libxml2 && \
    # CVE-2023-44431 & CVE-2023-51596
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libbluetooth3 && \
    # Remove libldap-2.5-0 to fix CVE-2023-2953
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y libldap-2.5-0 && \
    # Remove perl to fix CVE-2023-31484
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge --allow-remove-essential -y perl-base && \
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y perl-modules-5.36 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Remove libz1g to fix CVE-2023-45853
# WARNING: This will uninstall the package manager, which will prevent us from removing other packages, so this should be done last
RUN dpkg --purge --force-all zlib1g

# Copy extracted libz shared objects from stage 1
COPY --from=zlib-extract /tmp/libz.so.1 /usr/lib/x86_64-linux-gnu/libz.so.1
COPY --from=zlib-extract /tmp/libz.so.1.2.13 /usr/lib/x86_64-linux-gnu/libz.so.1.2.13

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
