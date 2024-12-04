TAG=test:0.0.1

all: build

build:
	docker build -t ${TAG} .

docker-build: build
