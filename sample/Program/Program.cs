using System;
using System.Web;
using System.Configuration;
using System.Threading.Tasks;
using System.Data.SqlClient;

class Program
{
    static void Main()
    {
        var user = HttpContext.Current?.User?.Identity?.Name;
        var setting = ConfigurationManager.AppSettings["ConnectionString"];
        Task.Factory.StartNew(() => Console.WriteLine("Old threading model"));
        SqlConnection conn = new SqlConnection(setting);
        conn.Open();
    }
}
