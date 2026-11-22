package oidc

import "time"

// SetRefreshWindow lets tests shorten the minimum time between JWKS refreshes.
func (v *OIDCValidator) SetRefreshWindow(d time.Duration) { v.keys.minRefresh = d }
