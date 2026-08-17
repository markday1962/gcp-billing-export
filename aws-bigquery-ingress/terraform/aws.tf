# Part 2 — AWS side: let a GCP service account assume a role (no static keys)

# Fetches the TLS cert thumbprint AWS needs to validate the OIDC provider,
# instead of hardcoding a fingerprint (certs/chains can rotate). AWS mostly
# validates the JWKS endpoint's TLS cert against its own trusted CA bundle
# and only falls back to this thumbprint if that fails, per AWS's docs — but
# a thumbprint is still a required field, and AWS wants the top intermediate
# CA that signed the leaf cert. terraform-provider-tls's `certificates` list
# comes back root-first (root, intermediate, leaf), so that's index 1.
data "tls_certificate" "google" {
  url = "https://accounts.google.com"
}

resource "aws_iam_openid_connect_provider" "google" {
  url = "https://accounts.google.com"
  # Google's minted ID tokens carry both `aud` and `azp` claims — per AWS's
  # OIDC docs, "If your OIDC identity provider is setting both aud and azp
  # claims in the token, AWS STS will use the value in the azp claim as the
  # aud claim." Google sets azp to the calling service account's OAuth
  # client ID (== its `unique_id`), NOT the requested audience string, so
  # that's what has to go in client_id_list/the trust condition — using the
  # SA's email here (matching the token's literal `aud` claim) causes every
  # AssumeRoleWithWebIdentity call to fail with InvalidIdentityToken, even
  # though the token is otherwise perfectly valid.
  client_id_list  = [google_service_account.cur_importer.unique_id]
  thumbprint_list = [data.tls_certificate.google.certificates[1].sha1_fingerprint]
}

data "aws_iam_policy_document" "cur_bigquery_import_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.google.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "accounts.google.com:aud"
      values   = [google_service_account.cur_importer.unique_id]
    }
  }
}

resource "aws_iam_role" "cur_bigquery_import" {
  name               = "cur-bigquery-import-role"
  assume_role_policy = data.aws_iam_policy_document.cur_bigquery_import_trust.json
}

data "aws_iam_policy_document" "cur_bigquery_import_s3" {
  statement {
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      "arn:aws:s3:::${var.cur_bucket_name}",
      "arn:aws:s3:::${var.cur_bucket_name}/*",
    ]
  }
}

resource "aws_iam_role_policy" "cur_bigquery_import_s3" {
  name   = "cur-bucket-read-only"
  role   = aws_iam_role.cur_bigquery_import.id
  policy = data.aws_iam_policy_document.cur_bigquery_import_s3.json
}
