FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt pyproject.toml uv.lock ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x run.sh
EXPOSE 8050
CMD ["./run.sh"]
