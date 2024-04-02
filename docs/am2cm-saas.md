# HDP to CDP One (SaaS) configuration migration


> **_NOTE:_** Migration to CDP SaaS is no longer supported, the following document is kept for the record

## Migrating Configurations from HDP to CDP as a Service

Using the tools downloaded from the Software Download Matrix, migrate the configurations from the HDP cluster to CDP One.

1. Download the packages to a host that has access to the HDP cluster and the CDP One clusters.

2. After downloading the package, extract the following zipped files:
    ```shell
    tar xzf am2cm-tool-2.3.0.0.tar.gz
    tar xzf am2cm-upgrade-tool-2.3.0.0.tar.gz
    tar xzf am2cm-diff-2.3.0.0.tar.gz
    ```
3. Enter into the extracted am2cm-2.3.0.0 folder.
    ```shell
    cd am2cm-2.3.0.0 
    ```

4. Create an output directory where the tools can generate the results
    ```shell
    export AM2CM_OUTPUT_DIR=/path/to/output/dir
    ```
5. Run the HDP Configuration Upgrader tool with following parameters  
    ```shell
    am2cm-upgrade/hdp-config-upgrade.sh -a <ambari_hostname> -c <cluster_name> [-P <ambari_port>] [--ssl] [-u <admin_user>] [-p <admin_password>]
    ```
6. Run the Cluster Topology Scanner tool to register the SaaS clusters
   
    The default way to access the CDP One clusters is using Knox JWT tokens, but if the client has direct access to the clusters, the tools can be used with BASIC authentication.
    <br></br>
   1. Register the data lake cluster
      </br>To generate a datalake token, follow the token generation steps.
      ```shell
      export TOKEN_DATALAKE=<jwt_token_datalake>
      am2cm-tool/cluster-scanner.sh -cm <target_base_url_datalake> -c <cluster_name> -t "$TOKEN_DATALAKE" [-cma <cm_api_endpoint>]
      ```
      - The _jwt_token_datalake_ must match the "_JWT Token_" value on the data lake's token generation page
      - The _target_base_url_datalake_ must match the "_Target Base URL_" value on the data lake's token generation page
      - The  **_**-cma <cm_api_endpoint>**_** option must be specified if the API endpoint of the CM server is different to the default '_/cm-api_'

      <br></br>
      However, if you have direct access to the cluster, you can use it with basic authentication.
      ```shell
      am2cm-tool/cluster-scanner.sh -cm <cm_base_url> -c <cluster_name> -au BASIC [-u <admin_user>] [-p <admin_password>] [-cma <cm_api_endpoint>]
      ```
      - The _cm_base_url_ must be specified in the following form: _**http(s)://<cm_hostname>:<cm_port>**_ eg: https://my-cm-server:7183
      - The _-u <admin_user>_ option must be specified if the admin user is different to the default '_admin_'
      - The _-p <admin_password>_ option must be specified if it is different to the default '_admin_'
      - The _-cma <cm_api_endpoint>_ option must be specified if the API endpoint of the CM server is different to the default '_/api_'
      <br/><br/>
      
   2. Register the data hub cluster
      <br/><br/>
      To generate a datahub cluster token, follow the token generation steps.
      ```shell
      export TOKEN_DATAHUB=<jwt-token-datahub>
      am2cm-tool/cluster-scanner.sh -cm <target_base_url_datahub> -c <cluster_name> -t "$TOKEN_DATAHUB" [--append] [-cma <cm_api_endpoint>]
      ```
       - The _jwt-token-datahub_ must match the "_JWT Token_" value on the data hub's token generation page
       - The _target_base_url_datahub_ must match the "_Target Base URL_" value on the data hub's token generation page
       - The _--append_ parameter must be specified if we want to process the datahub cluster together with the data lake (or other previously registered clusters)   
       - The _-cma <cm_api_endpoint>_ option must be specified if the API endpoint of the CM server is different to the default '_/cm-api_'
      
      ---
        **NOTE** 
        If you have direct access to the cluster, you can use it with basic authentication as above for the data lake.
   
      ---

   The generated cluster-topology.yml will be placed into the am2cm-tool/conf folder.

7. Run the AM2CM SaaS tool to generate the CDP One cluster blueprints from the service_topology.yaml and HDP7_blueprint.json files
    ```shell
    am2cm-tool/am2cm-saas.sh -sv <hdp_version> [-tv <public_cloud_version>]
    ```
    The blueprints in $AM2CM_OUTPUT_DIR can be used to create CDP Public Cloud clusters. However, for CDP One clusters, the **config_upload.sh** will update the configurations through Cloudera Manager API.

8. Edit configurations if needed in blueprints in the **$AM2CM_OUTPUT_DIR** dir
   
    1. To differentiate the HDP2/3 and CDP One configurations, run the following command:
       ```shell
       am2cm-diff/am2cm-diff.sh -sumdir $AM2CM_OUTPUT_DIR 
       ```
    2. If you do not want to modify or migrate some existing configurations on the previously registered clusters, add them to the _am2cm-tool/conf/service-ignore-config-<public_cloud_version>-saas.ini_ file.
   
9. Run the Config Uploader tool to upload configurations to the previously registered Data Lake and DataHub clusters
   
     If a cluster was previously registered using a JWT token, the token must be re-entered during processing the cluster, as JWT tokens are typically short-lived.
     So if the previous token has expired, before issuing the command make sure to generate a new one and assign it to an environment variable. After issuing the command you will be prompted for the token, you have to pass it as a linux variable.
     <br/>eg.: _Enter the access token (or the assigned environment variable) for the CM server: **$TOKEN_DATAHUB**_
    ```shell
    am2cm-tool/config_upload.sh
    ``` 
    
    
11. If the CDP One cluster is not configured correctly, then you must perform from step 8 again.
