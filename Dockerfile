FROM python:3
WORKDIR /email_unsubscriber
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "unsubscriber.py"]