package de.legalhub.fakeagency.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("Fake Legal Partner Agency Simulator API")
                        .version("1.0.0")
                        .description("Multi-Agency Legal Partner simulation endpoints for CaseForce LegalHub webhook integration, subscription management, and HMAC-SHA256 signature verification.")
                        .contact(new Contact()
                                .name("LegalHero Engineering")
                                .email("tech@legalhero.de"))
                        .license(new License()
                                .name("Apache 2.0")
                                .url("https://www.apache.org/licenses/LICENSE-2.0")));
    }
}
