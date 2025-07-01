FROM python:3.12-slim

ENV TZ=Europe/Zurich
RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && apt-get clean

# Set working directory and copy there
WORKDIR /app
COPY . /app

# Install dependencies
RUN pip install --upgrade pip --break-system-packages && \
    pip install --no-cache-dir -r requirements.txt


ENV PYTHONUNBUFFERED=1

CMD ["python", "wsgi.py"]
