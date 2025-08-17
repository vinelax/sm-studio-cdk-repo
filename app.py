#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Environment

from sm_cdk_app.sm_cdk_app_stack import SageMakerStudioPublicStack
from oidc_stack.oidc_stack import OidcRoleStack

app = cdk.App()

env = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT") or os.getenv("AWS_ACCOUNT_ID"),
    region =os.getenv("CDK_DEFAULT_REGION")  or os.getenv("AWS_REGION") or "eu-central-1",
)

# Main stack (example resources)
SageMakerStudioPublicStack(app, "SageMakerStudioPublicStack", env=env)

# One-time: creates GitHub OIDC role in AWS account.
# OidcRoleStack(app, "OidcRoleStack", env=env)

app.synth()
