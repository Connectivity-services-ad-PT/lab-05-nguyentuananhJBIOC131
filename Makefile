.PHONY: compose-up compose-down logs test-compose

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down -v

logs:
	docker compose logs -f

test-compose:
	npx newman run postman/collections/FIT4110_lab04_iot_docker.postman_collection.json \
		-e postman/environments/FIT4110_lab05_local.postman_environment.json \
		-r cli,html,xml --reporter-html-export reports/newman-lab05-compose.html