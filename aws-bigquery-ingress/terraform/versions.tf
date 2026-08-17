terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
}

# The centralized Artifact Registry repo (`ufonia`) lives in a different
# project than the CUR importer's own resources.
provider "google" {
  alias   = "shared_services"
  project = var.image_repo_project
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}
