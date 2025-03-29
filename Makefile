reattach:
	docker-compose down
	docker-compose up -d
	docker exec -it research_gstreamer bash

attach:
	docker exec -it research_gstreamer bash

build:
	docker-compose up --build -d
