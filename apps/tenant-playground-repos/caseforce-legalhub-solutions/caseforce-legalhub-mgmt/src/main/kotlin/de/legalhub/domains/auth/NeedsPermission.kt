package de.legalhub.domains.auth

import io.micronaut.aop.Around
import io.micronaut.context.annotation.Type

@MustBeDocumented
@Target(AnnotationTarget.FUNCTION)
@Retention(AnnotationRetention.RUNTIME)
@Around
@Type(NeedsPermissionInterceptor::class)
annotation class NeedsPermission(
    val value: Permission
)
