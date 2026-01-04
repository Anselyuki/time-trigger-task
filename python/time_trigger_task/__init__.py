from time_trigger_task import task_io


if __name__ == '__main__':
    configs = task_io.list_configs("configs")
    print(configs)
