from aws_cdk import (
    Stack,
    Aws,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_sagemaker as sagemaker,
    CfnOutput,
)
from constructs import Construct


class SageMakerStudioPublicStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC: reuse default 
        vpc = ec2.Vpc.from_lookup(self, "Vpc", is_default=True)
        subnet_ids = vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnet_ids[:2]

        # Security group for Studio apps
        studio_sg = ec2.SecurityGroup(
            self, "StudioSG", vpc=vpc, allow_all_outbound=True, description="SageMaker Studio apps"
        )

        # Execution role: reuse or create (based on context)
        exec_role_arn = self.node.try_get_context("StudioExecutionRoleArn") or ""
        if exec_role_arn:
            exec_role = iam.Role.from_role_arn(self, "StudioExecRole", exec_role_arn, mutable=False)
        else:
            prefix = self.node.try_get_context("StudioExecRoleNamePrefix") or "SageMakerExecRole"
            exec_role = iam.Role(
                self, "StudioExecRole",
                role_name=f"{prefix}-public",
                assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
                description="Execution role for SageMaker Studio (PublicInternetOnly)",
            )
            # Starting broad for dev
            exec_role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            )

        # Studio Domain (PublicInternetOnly)
        domain = sagemaker.CfnDomain(
            self, "StudioDomain",
            auth_mode="IAM",
            domain_name="studio-domain-public",
            vpc_id=vpc.vpc_id,
            subnet_ids=subnet_ids,
            app_network_access_type="PublicInternetOnly",
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=exec_role.role_arn,
                security_groups=[studio_sg.security_group_id],
            ),
        )

        # One user
        user = sagemaker.CfnUserProfile(
            self, "StudioUser",
            domain_id=domain.attr_domain_id,
            user_profile_name="admin-user",
        )
        user.add_dependency(domain)

        CfnOutput(self, "VpcId", value=vpc.vpc_id)
        CfnOutput(self, "SubnetIds", value=",".join(subnet_ids))
        CfnOutput(self, "StudioDomainId", value=domain.attr_domain_id)
        CfnOutput(self, "StudioUserName", value=user.user_profile_name)
        CfnOutput(
            self,
            "StudioConsoleUrl",
            value=f"https://{Aws.REGION}.console.aws.amazon.com/sagemaker/home?region={Aws.REGION}"
                  f"#/studio/domains/{domain.attr_domain_id}/user-profiles/{user.user_profile_name}"
        )

  