ARG BUILD_FROM
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    ffmpeg \
    curl \
    py3-pip \
    py3-pillow \
    py3-aiohttp \
    py3-aiofiles \
    py3-numpy \
    zbar \
    py3-zbar \
    python3 \
    python3-dev \
    py3-virtualenv \
    gcc \
    musl-dev \
    linux-headers \
    libffi-dev \
    openssl-dev \
    cmake \
    make \
    py3-opencv \
    py3-gtts \
    py3-pyzbar \
    py3-flask \
    py3-jinja2 \
    py3-werkzeug \
    py3-markupsafe \
    py3-itsdangerous \
    py3-requests \
    py3-click \
    py3-six \
    py3-yaml

# Create virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install additional Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir requests pyyaml

# Copy all necessary files
COPY run.sh /
COPY server.py /app/
COPY tts_generate_openipc.sh /app/
COPY tts_generate.sh /app/
COPY check_modules.py /app/
COPY templates/ /app/templates/

# Make scripts executable
RUN chmod a+x /run.sh && \
    chmod a+x /app/tts_generate_openipc.sh && \
    chmod a+x /app/tts_generate.sh && \
    chmod a+x /app/check_modules.py

# Create working directory
WORKDIR /app

CMD [ "/run.sh" ]