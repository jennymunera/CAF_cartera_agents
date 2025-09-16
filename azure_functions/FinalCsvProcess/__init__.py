import logging
import os
import azure.functions as func
from shared_code.utils.processor_csv import process_ndjson_or_json_to_csv
from shared_code.utils.build_email_payload import build_email_payload
from shared_code.utils.notifications_service import NotificationsService

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("HTTP trigger function processed a request.")
    try:
      
        AZURE_STORAGE_OUTPUT_CONNECTION_STRING = os.environ["AZURE_STORAGE_OUTPUT_CONNECTION_STRING"]
        CONTAINER_OUTPUT_NAME = os.environ["CONTAINER_OUTPUT_NAME"]  
        NOTIFICATION_API_URL = os.environ["NOTIFICATIONS_API_URL_BASE"]
        SHAREPOINT_FOLDER = os.environ["SHAREPOINT_FOLDER"]    

        folder_name = req.params.get("folderName")

        input_files = ["auditoria.json", "productos.json", "desembolsos.json"]
        output_files = ["auditoria_cartera.csv", "producto_cartera.csv", "desembolso_cartera.csv"]    

        logging.info("Llamando a la funcion: process_ndjson_or_json_to_csv.") 
   
        for input_file, output_file in zip(input_files, output_files):
            input_path = f"basedocuments/{folder_name}/results/{input_file}"
            output_path = f"outputdocuments/{output_file}"
            
            logging.info(f"Procesando {input_file} -> {output_file}")
            process_ndjson_or_json_to_csv(
                AZURE_STORAGE_OUTPUT_CONNECTION_STRING,
                CONTAINER_OUTPUT_NAME,
                input_path,
                output_path
            )
        email_payload= build_email_payload("SUCCESS_FINALLY_PROCESS", folder_name, SHAREPOINT_FOLDER)
        email_notification_service = NotificationsService(NOTIFICATION_API_URL)
        email_notification_service.send(email_payload)

        return func.HttpResponse(
                "Finalizado con éxito",
                status_code=200,
                mimetype="application/json"
            )
       
    except Exception as e:
       logging.error(f"Error HttpRequest: {e}")
       return func.HttpResponse(
                f"Error en la solicitud HTTP: {e}",
                status_code=500
            )