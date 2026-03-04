FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/forecast_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/forecast_service/app ./app
COPY services/common ./services/common

RUN python -c "from services.common.sagemaker_client import invoke_endpoint_raw; print('invoke_endpoint_raw ok')"

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
