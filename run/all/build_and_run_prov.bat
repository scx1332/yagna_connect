docker-compose build centralnet prov1
docker-compose kill centralnet prov1
docker-compose up -d centralnet prov1
docker-compose logs -f centralnet prov1