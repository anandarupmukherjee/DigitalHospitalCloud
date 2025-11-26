# Digital Hospitals Cloud

Digital Hospitals Cloud is a comprehensive platform designed to manage various hospital inventories and logistics. It features a centralized dashboard that orchestrates access to specialized applications for Histopathology, Genomics, and Logistics Tracking.

## Key Features

-   **Centralized Dashboard**: A single entry point to access all hospital management applications.
-   **Histopathology Inventory**: Manage samples, slides, and inventory for histopathology labs.
-   **Genomics Inventory**: Track genomics samples, reagents, and workflows.
-   **Logistics Tracking**: Monitor shipments and logistics for hospital supplies.
-   **Dockerized Architecture**: Easy deployment and management using Docker containers.
-   **Nginx Reverse Proxy**: Efficient routing and load balancing for all services.

## Architecture

The project consists of the following services:

-   **Dashboard**: A Flask-based application that serves as the main landing page and status monitor.
-   **Nginx**: A reverse proxy that routes traffic to the appropriate service based on the URL path.
-   **Histopath Web**: Django application for Histopathology Inventory.
-   **Genomics Web**: Django application for Genomics Inventory.
-   **Logistics Tracking Web**: Django application for Logistics Tracking.

## Prerequisites

-   [Docker](https://www.docker.com/get-started)
-   [Docker Compose](https://docs.docker.com/compose/install/)

## Installation & Usage

### Using Docker Compose (Recommended)

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/anandarupmukherjee/DigitalHospitalCloud.git
    cd DigitalHospitalCloud
    ```

2.  **Start the services:**

    ```bash
    docker-compose up -d --build
    ```

3.  **Access the application:**

    Open your browser and navigate to `http://localhost`. You will see the central dashboard with links to all applications.

    -   **Dashboard**: `http://localhost/`
    -   **Histopathology**: `http://localhost/histopath/`
    -   **Genomics**: `http://localhost/genomics/`
    -   **Logistics**: `http://localhost/tracker/`

### Local Development (Without Docker)

You can also run the applications locally using the provided scripts.

1.  **Start all applications:**

    ```bash
    ./start_all.sh
    ```

2.  **Stop all applications:**

    ```bash
    ./stop_all.sh
    ```

## Project Structure

-   `dashboard/`: Contains the Flask dashboard application.
-   `nginx/`: Nginx configuration files.
-   `InventoryManagementHistopath/`: Source code for the Histopathology application.
-   `InventoryManagementGenomics/`: Source code for the Genomics application.
-   `logistics-tracking-platform/`: Source code for the Logistics Tracking application.
-   `docker-compose.yml`: Docker Compose configuration.
