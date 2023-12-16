FROM python:3.11-alpine
WORKDIR /tmp
COPY ./requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PORT=8080
ENV APP_DIR=/opt
ENV NUM_WORKERS=1
COPY app.py $APP_DIR
COPY main.py $APP_DIR
#COPY settings.yaml $APP_DIR
COPY templates $APP_DIR/templates
ENTRYPOINT cd $APP_DIR && hypercorn -b 0.0.0.0:$PORT -w $NUM_WORKERS --access-logfile '-' app:app
EXPOSE $PORT
