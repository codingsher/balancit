.PHONY: cluster-up cluster-down build load deploy reset clean
.PHONY: logs-a logs-b logs-otel
.PHONY: forward-prometheus forward-grafana forward-a forward-b
.PHONY: traffic-test

# Cluster lifecycle
cluster-up:
	kind create cluster --config k8s/kind-config.yaml

cluster-down:
	kind delete cluster --name balancit
	docker system prune -af --volumes

# Build & load images
build:
	docker build -t service-a:latest backend-services/service-a/
	docker build -t service-b:latest backend-services/service-b/

load:
	kind load docker-image service-a:latest --name balancit
	kind load docker-image service-b:latest --name balancit

# Deploy
deploy:
	kubectl apply -f k8s/base/namespace.yaml
	kubectl apply -f k8s/base/service-a.yaml
	kubectl apply -f k8s/base/service-b.yaml
	kubectl apply -f k8s/base/otel-collector.yaml

deploy-monitoring:
	helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
	  --namespace monitoring --create-namespace \
	  --set grafana.adminPassword=admin123 \
	  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
	  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false
	kubectl apply -f k8s/monitoring/podmonitor.yaml

# Fll reset (when something is broken)
reset: cluster-down cluster-up build load deploy deploy-monitoring

# Logs
logs-a:
	kubectl logs -f -n balancit deployment/service-a

logs-b:
	kubectl logs -f -n balancit deployment/service-b

logs-otel:
	kubectl logs -f -n balancit deployment/otel-collector

# Port-forwards
forward-prometheus:
	kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

forward-grafana:
	kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

forward-a:
	kubectl port-forward -n balancit svc/service-a 8000:8000

forward-b:
	kubectl port-forward -n balancit svc/service-b 8001:8000

# Sanity test
traffic-test:
	@echo "Sending test traffic to service-a (assumes forward-a is running)..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
	  curl -s -H "X-Client-ID: test-$$i" localhost:8000/api/cpu > /dev/null; \
	  curl -s -H "X-Client-ID: test-$$i" localhost:8000/api/light > /dev/null; \
	done
	@echo "Done."
