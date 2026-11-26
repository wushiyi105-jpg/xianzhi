FROM python:3.10-slim

LABEL org.opencontainers.image.source="https://github.com/wushiyi105-jpg/xianzhi" \
      org.opencontainers.image.description="闲置 · 二手定价与挂牌文案:折旧、平台到手价、砍价应答" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8000

CMD ["python", "-m", "xianzhi", "web", "--host", "0.0.0.0"]
