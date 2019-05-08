FROM python:3.7-slim
RUN apt-get -yqq update && apt-get install -yqq g++ libopenblas-base libopenblas-dev swig
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8000
VOLUME /app/final.mdl
ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
CMD ["app:app"]
