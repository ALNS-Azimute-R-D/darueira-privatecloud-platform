package config

import (
	"os"
)

type Config struct {
	Port         string
	OpenFGAURL   string
	StoreID      string
	ModelID      string
	OIDCIssuer   string
	OIDCSecret   string
	KafkaBrokers string
	KafkaTopic   string
}

func Load() *Config {
	return &Config{
		Port:         getEnv("PORT", "8080"),
		OpenFGAURL:   getEnv("OPENFGA_API_URL", "http://openfga.drr-corpshared-plat.svc.cluster.local:8080"),
		StoreID:      getEnv("OPENFGA_STORE_ID", ""),
		ModelID:      getEnv("OPENFGA_MODEL_ID", ""),
		OIDCIssuer:   getEnv("OIDC_ISSUER_URL", "http://authentik-server.drr-corpshared-plat.svc.cluster.local:9000/application/o/darueira/"),
		OIDCSecret:   getEnv("OIDC_CLIENT_SECRET", ""),
		KafkaBrokers: getEnv("KAFKA_BROKERS", "kafka-cluster-kafka-bootstrap.drr-corpshared-plat.svc.cluster.local:9092"),
		KafkaTopic:   getEnv("KAFKA_TUPLE_TOPIC", "drr.authz.tuple-events"),
	}
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok && value != "" {
		return value
	}
	return fallback
}
