package config

import (
	"os"
)

type Config struct {
	Port         string
	MetricsPort  string
	Version      string
	OpenFGAURL   string
	StoreID      string
	ModelID      string
	OIDCIssuer   string
	OIDCJWKSURL  string
	OIDCAudience string
	KafkaBrokers string
	KafkaTopic   string
}

func Load() *Config {
	return &Config{
		Port:         getEnv("PORT", "8080"),
		MetricsPort:  getEnv("METRICS_PORT", "9102"),
		Version:      getEnv("APP_VERSION", "dev"),
		OpenFGAURL:   getEnv("OPENFGA_API_URL", "http://openfga.drr-corpshared-plat.svc.cluster.local:8080"),
		StoreID:      getEnv("OPENFGA_STORE_ID", ""),
		ModelID:      getEnv("OPENFGA_MODEL_ID", ""),
		// No defaults for token validation: without an issuer and a JWKS URL every token is rejected (ADR-0022).
		OIDCIssuer:   getEnv("OIDC_ISSUER_URL", ""),
		OIDCJWKSURL:  getEnv("OIDC_JWKS_URL", ""),
		OIDCAudience: getEnv("OIDC_AUDIENCE", ""),
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
