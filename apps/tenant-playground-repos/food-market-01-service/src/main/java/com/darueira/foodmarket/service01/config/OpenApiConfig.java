package com.darueira.foodmarket.service01.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Value("${app.market-id:MKT-EU-01-SPRING}")
    private String marketId;

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("Food Market 01 Service API (Java 25 / Spring Boot 3.4)")
                        .version("1.0.0")
                        .description("Hexagonal Architecture REST API & Real-Time SSE Stream for B2B European Food Trading (Tenant: swfabrik-europe, Market: " + marketId + ")")
                        .contact(new Contact()
                                .name("SW Fabrik Europe Architecture Team")
                                .email("architecture@swfabrik-europe.local"))
                        .license(new License()
                                .name("Apache 2.0")
                                .url("https://darueira.local/licenses")));
    }
}
