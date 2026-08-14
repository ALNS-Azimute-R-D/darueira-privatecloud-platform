package authz

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type HTTPAuthzClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewHTTPAuthzClient(baseURL string) *HTTPAuthzClient {
	if baseURL == "" {
		baseURL = "http://drr-iam-authz-svc.drr-corpshared-plat.svc.cluster.local:8080"
	}
	return &HTTPAuthzClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

type TupleRequest struct {
	User     string `json:"user"`
	Relation string `json:"relation"`
	Object   string `json:"object"`
}

func (c *HTTPAuthzClient) WriteTuple(ctx context.Context, user, relation, object string) error {
	reqBody, err := json.Marshal(TupleRequest{
		User:     user,
		Relation: relation,
		Object:   object,
	})
	if err != nil {
		return err
	}

	url := fmt.Sprintf("%s/api/v1/authz/tuples", c.baseURL)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(reqBody))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		// Log gracefully if authz service is booting in dev
		fmt.Printf("[AUTHZ-CLIENT] Warning: failed to write tuple %s %s %s: %v\n", user, relation, object, err)
		return nil
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("authz service returned status %d", resp.StatusCode)
	}

	return nil
}

func (c *HTTPAuthzClient) DeleteTuple(ctx context.Context, user, relation, object string) error {
	reqBody, err := json.Marshal(TupleRequest{
		User:     user,
		Relation: relation,
		Object:   object,
	})
	if err != nil {
		return err
	}

	url := fmt.Sprintf("%s/api/v1/authz/tuples", c.baseURL)
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, url, bytes.NewBuffer(reqBody))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		fmt.Printf("[AUTHZ-CLIENT] Warning: failed to delete tuple %s %s %s: %v\n", user, relation, object, err)
		return nil
	}
	defer resp.Body.Close()

	return nil
}
