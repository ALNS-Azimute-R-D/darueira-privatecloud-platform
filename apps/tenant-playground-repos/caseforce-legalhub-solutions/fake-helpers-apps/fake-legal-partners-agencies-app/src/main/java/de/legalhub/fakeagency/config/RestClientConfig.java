package de.legalhub.fakeagency.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.converter.ByteArrayHttpMessageConverter;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.web.client.RestClient;

@Configuration
public class RestClientConfig {

    @Value("${caseforce.api.base-url:http://localhost:8080}")
    private String caseforceBaseUrl;

    @Bean
    @ConditionalOnMissingBean(name = "caseforceRestClient")
    public RestClient caseforceRestClient(CaseforceAuthInterceptor authInterceptor, ObjectMapper objectMapper) {
        return RestClient.builder()
                .baseUrl(caseforceBaseUrl)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .messageConverters(converters -> {
                    converters.clear();
                    converters.add(new ByteArrayHttpMessageConverter());
                    converters.add(new StringHttpMessageConverter());
                    converters.add(new MappingJackson2HttpMessageConverter(objectMapper));
                })
                .requestInterceptor(authInterceptor)
                .build();
    }
}
