terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
}

# The centralized Artifact Registry repo (`ufonia`) lives in a different
# project than this pipeline's own resources.
provider "google" {
  alias   = "shared_services"
  project = var.image_repo_project
}
