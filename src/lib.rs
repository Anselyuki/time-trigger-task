use glob::glob;
use pyo3::prelude::*;

// 1. 扫描目录获取 .json 文件列表
#[pyfunction]
#[pyo3(name = "list_configs")]
fn list_configs(dir: String) -> PyResult<Vec<String>> {
    let pattern = format!("{}/*.json", dir);
    let mut files = Vec::new();

    if let Ok(paths) = glob(&pattern) {
        for entry in paths {
            if let Ok(path) = entry {
                if let Some(path_str) = path.to_str() {
                    files.push(path_str.to_string());
                }
            }
        }
    }
    // 排序，保证执行顺序稳定
    files.sort();
    Ok(files)
}

// 注册模块 — 使用 `task_io` 扩展名，和包内模块名一致
#[pymodule]
fn task_io(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(list_configs, m)?)?;
    Ok(())
}
