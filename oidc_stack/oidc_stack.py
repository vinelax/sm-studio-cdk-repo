from aws_cdk import (
    Stack,
    Aws,
    CfnOutput,
    aws_iam as iam,
)
from constructs import Construct

class OidcRoleStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read GitHub repo info from context
        owner = self.node.try_get_context("GitHubRepoOwner")
        repo = self.node.try_get_context("GitHubRepoName")
        branch = self.node.try_get_context("GitHubBranch") or "main"

        # Create the execution role
        studio_exec_role_arn   = self.node.try_get_context("StudioExecutionRoleArn") or ""  
        create_exec_role = str(self.node.try_get_context("CreateStudioExecutionRole") or "false").lower() == "true"
        exec_role_name_prefix = self.node.try_get_context("StudioExecRoleNamePrefix") or "SageMakerExecRole"
        wf_file = self.node.try_get_context("GitHubWorkflowFile") or "cdk-deploy.yml"

        if not owner or not repo:
            raise ValueError("Set GitHubRepoOwner and GitHubRepoName in cdk.json context.")

        # ---- GitHub OIDC provider -------------------------------------------
        provider = iam.OpenIdConnectProvider(
            self, "GitHubProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
        )

        # Only allow this repo/branch to assume the role
        principal = iam.FederatedPrincipal(
            provider.open_id_connect_provider_arn,
            conditions={
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": f"repo:{owner}/{repo}:ref:refs/heads/{branch}",
                    "token.actions.githubusercontent.com:job_workflow_ref":
                    f"{owner}/{repo}/.github/workflows/{wf_file}@refs/heads/{branch}",
                },
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                },
            },
            assume_role_action="sts:AssumeRoleWithWebIdentity",
        )

        gh_role = iam.Role(
            self,
            "GitHubActionsRole",
            assumed_by=principal,
            description="Least-privilege role for GitHub Actions CDK deploys of SageMaker Studio",
        )

        # ---- Inline least-privilege policy ----------------------------------
        statements: list[iam.PolicyStatement] = []

        # 1) CloudFormation
        statements.append(iam.PolicyStatement(
            sid="CloudFormationDeploy",
            effect=iam.Effect.ALLOW,
            actions=[
                "cloudformation:CreateStack", "cloudformation:UpdateStack", "cloudformation:DeleteStack",
                "cloudformation:Describe*", "cloudformation:GetTemplate", "cloudformation:List*",
                "cloudformation:CreateChangeSet", "cloudformation:ExecuteChangeSet", "cloudformation:DeleteChangeSet",
                "cloudformation:TagResource", "cloudformation:UntagResource",
            ],
            resources=["*"],
        ))

        # 2) SageMaker Studio (Domain/UserProfile lifecycle + describes/lists)
        statements.append(iam.PolicyStatement(
            sid="SageMakerStudio",
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:CreateDomain", "sagemaker:UpdateDomain", "sagemaker:DeleteDomain",
                "sagemaker:CreateUserProfile", "sagemaker:UpdateUserProfile", "sagemaker:DeleteUserProfile",
                "sagemaker:Describe*", "sagemaker:List*",
            ],
            resources=["*"],
        ))

        # 3) EC2 lookups + security group mgmt (CDK lookups + Studio SG)
        statements.append(iam.PolicyStatement(
            sid="Ec2LookupsAndSecurityGroups",
            effect=iam.Effect.ALLOW,
            actions=[
                "ec2:DescribeVpcs", "ec2:DescribeSubnets", "ec2:DescribeRouteTables",
                "ec2:DescribeAvailabilityZones", "ec2:DescribeSecurityGroups",
                "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup",
                "ec2:AuthorizeSecurityGroupIngress", "ec2:AuthorizeSecurityGroupEgress",
                "ec2:RevokeSecurityGroupIngress", "ec2:RevokeSecurityGroupEgress",
                "ec2:CreateTags", "ec2:DeleteTags",
            ],
            resources=["*"],
        ))

        # 4) CloudWatch Logs (basic create/put for constructs that emit logs)
        statements.append(iam.PolicyStatement(
            sid="CloudWatchLogsBasic",
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                "logs:DescribeLogGroups", "logs:DescribeLogStreams",
            ],
            resources=["*"],
        ))

        # 5) Allow creating SageMaker's service-linked role if not present
        statements.append(iam.PolicyStatement(
            sid="CreateServiceLinkedRoleForSageMaker",
            effect=iam.Effect.ALLOW,
            actions=["iam:CreateServiceLinkedRole"],
            resources=["*"],
            conditions={"StringEquals": {"iam:AWSServiceName": "sagemaker.amazonaws.com"}},
        ))

        # 6) Pass the Studio execution role (when REUSING an existing role)
        if studio_exec_role_arn:
            statements.append(iam.PolicyStatement(
                sid="PassStudioExecutionRole",
                effect=iam.Effect.ALLOW,
                actions=["iam:PassRole"],
                resources=[studio_exec_role_arn],
                conditions={"StringEquals": {"iam:PassedToService": "sagemaker.amazonaws.com"}},
            ))

        # 7) Allow CI to CREATE the execution role (scoped by prefix)
        if create_exec_role:
            statements.append(iam.PolicyStatement(
                sid="IamForStudioExecutionRole",
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
                    "iam:AttachRolePolicy", "iam:DetachRolePolicy",
                    "iam:PutRolePolicy", "iam:DeleteRolePolicy",
                    "iam:TagRole", "iam:UntagRole", "iam:ListAttachedRolePolicies",
                ],
                resources=[f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/{exec_role_name_prefix}*"],
            ))

        # 9) Allow assuming the modern CDK bootstrap roles
        bootstrap_role_arns = [
            f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/cdk-hnb659fds-deploy-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/cdk-hnb659fds-file-publishing-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/cdk-hnb659fds-image-publishing-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/cdk-hnb659fds-lookup-role-{Aws.ACCOUNT_ID}-{Aws.REGION}",
        ]
        statements.append(iam.PolicyStatement(
            sid="AssumeCdkBootstrapRoles",
            effect=iam.Effect.ALLOW,
            actions=["sts:AssumeRole"],
            resources=bootstrap_role_arns,
        ))

        # Attach the inline policy
        iam.Policy(self, "GitHubActionsLeastPrivilege", statements=statements).attach_to_role(gh_role)

        CfnOutput(self, "GitHubActionsRoleArn", value=gh_role.role_arn)