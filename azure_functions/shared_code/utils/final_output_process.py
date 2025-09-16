import requests
import logging

def invoke_download_final_output(folder_name: str, api_key: str = None) -> str:
    """
    Invoca la Azure Function HttpTrigerTestEvent con los parámetros indicados.

    Args:
        folder_name (str): Nombre de la carpeta (folderName)
        api_key (str, opcional): API key de la Function si está protegida

    Returns:
        str: Texto de la respuesta de la Function destino
    """
    try:
        base_url = "https://azfunc-analisis-batch-mvp-cartera-cr-a7dhbkaeeshbd3ey.eastus-01.azurewebsites.net/api/FinalCsvProcess"


        params = {
            "folderName": folder_name
        }

        headers = {}
        if api_key:
            headers["x-functions-key"] = api_key

        logging.info(f"Invocando Function destino con params: {params}")
        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code == 200:
            logging.info("Invocación exitosa a la Function destino.")
            return response.text
        else:
            logging.error(f"Error {response.status_code} al invocar Function destino: {response.text}")
            return f"Error {response.status_code}: {response.text}"

    except Exception as e:
        logging.error(f"Excepción al invocar Function destino: {str(e)}")
        return